interface TutorialCardProps {
  icon: string;
  title: string;
  description: string;
  time: string;
  link: string;
}

const TutorialCard = ({ icon, title, description, time, link }: TutorialCardProps) => {
  return (
    <a 
      href={link} 
      target="_blank" 
      rel="noopener noreferrer"
      className="block bg-white rounded-lg shadow-sm border border-gray-100 hover:shadow-md transition-all duration-200 hover:border-solace-blue/30 group h-full"
    >
      <div className="p-5 flex flex-col h-full">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center">
            <span className="text-2xl mr-3">{icon}</span>
            <h4 className="text-lg font-medium text-gray-800 group-hover:text-solace-blue transition-colors">{title}</h4>
          </div>
          <div className="bg-gray-100 text-gray-600 px-3 py-1 rounded-full text-xs font-medium">
            {time}
          </div>
        </div>
        
        <p className="text-gray-600 text-sm flex-grow mb-4">
          {description}
        </p>
        
        <div className="mt-auto flex justify-end">
          <span className="text-solace-blue text-sm font-medium flex items-center group-hover:translate-x-1 transition-transform">
            View Tutorial
            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 ml-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </span>
        </div>
      </div>
    </a>
  );
};

export default TutorialCard;